#include <Arduino.h>
#include <string.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include "MIDIUSB.h" 
#include "const.h"

#define TCA_R_WIRE Wire1
#define TCA_WIRE Wire2
Adafruit_SSD1306 display(128, 32, &TCA_WIRE, -1);
Adafruit_SSD1306 display_r(128, 32, &TCA_R_WIRE, -1);

IntervalTimer scan_timer;
#define SYSEX_BUF_SIZE 128
/** Set to 0 to disable Serial spam from Ableton → controller MIDI/Sysex. */
#ifndef LOG_ABLETON_MIDI
#define LOG_ABLETON_MIDI 1
#endif
/** Cubefish knob sysex: ... enc, SYNC_TAG, midi_byte, display... */
#define CUBEFISH_KNOB_SYNC_TAG 0x01
byte sysex_buf[SYSEX_BUF_SIZE];
int sysex_index = 0;
uint8_t prev_display = TCA_R;
Adafruit_SSD1306* cur_display = NULL;
long startTime, endTime, elapsedTime;
uint8_t cur_channel = 1;
uint8_t selected_button = 0;
char display_text[16][DISPLAY_TEXT_LEN] = {0};

char button_text[8][DISPLAY_TEXT_LEN] = {0};
void scan_isr();


uint8_t layer_to_selected_bank[4] = {0};



int last_recv_encoder_val[16] = {0};
int encoder_wait[16] = {0}; // num ticks


Adafruit_SSD1306 * set_display(uint8_t bus){
    uint8_t addr = display_map[bus][0];
    uint8_t ch = display_map[bus][1];

    if (addr == TCA_R) {
      TCA_R_WIRE.beginTransmission(addr);
      TCA_R_WIRE.write(shifter << ch);
      TCA_R_WIRE.endTransmission();
      return &display_r;
    }

    if (prev_display != addr) {
      TCA_WIRE.beginTransmission(prev_display);
      TCA_WIRE.write(0);
      TCA_WIRE.endTransmission();
    }
    TCA_WIRE.beginTransmission(addr);
    TCA_WIRE.write(shifter << ch);
    TCA_WIRE.endTransmission();

    prev_display = addr;
    return &display;
}

void init_displays() {
  Serial.println("Initializing displayz");
  TCA_WIRE.beginTransmission(TCA_L);
  TCA_WIRE.write(0);
  TCA_WIRE.endTransmission();

  TCA_R_WIRE.beginTransmission(TCA_R);
  TCA_R_WIRE.write(0);
  TCA_R_WIRE.endTransmission();

  TCA_WIRE.beginTransmission(TCA_U);
  TCA_WIRE.write(0);
  TCA_WIRE.endTransmission();

  for (int channel = 0; channel < 20; channel++) {
    cur_display = set_display(channel);
    Serial.println(channel);
    if(!cur_display->begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
      Serial.println(F("SSD1306 allocation failed"));
      for(;;);
    }
    cur_display->clearDisplay();
    cur_display->setRotation(2);
    cur_display->setTextSize(2);
    cur_display->setTextColor(WHITE);
    cur_display->setCursor(45, 10);
    cur_display->println(channel);
    cur_display->display(); 
  }

  Serial.println("Initialized displays");
} 


void init_mux() {
  pinMode(SIG_L1, INPUT_PULLUP);
  pinMode(SIG_L2, INPUT_PULLUP);
  pinMode(SIG_R1, INPUT_PULLUP);
  pinMode(SIG_R2, INPUT_PULLUP);
  pinMode(SIG_U, INPUT_PULLUP);

  pinMode(S0_A, OUTPUT); 
  pinMode(S1_A, OUTPUT); 
  pinMode(S2_A, OUTPUT); 
  pinMode(S3_A, OUTPUT); 
  digitalWrite(S0_A, LOW);
  digitalWrite(S1_A, LOW);
  digitalWrite(S2_A, LOW);
  digitalWrite(S3_A, HIGH);

  pinMode(S0_B, OUTPUT); 
  pinMode(S1_B, OUTPUT); 
  pinMode(S2_B, OUTPUT); 
  pinMode(S3_B, OUTPUT); 
  digitalWrite(S0_B, LOW);
  digitalWrite(S1_B, LOW);
  digitalWrite(S2_B, LOW);
  digitalWrite(S3_B, HIGH);
}

void init_interrupts() {
  scan_timer.begin(scan_isr, 1000000 / SCAN_PER_SEC);
}

String channel_names[4] = {
  "Layer 1",
  "Layer 2",
  "Global",
  "FX"
};

String bank_names[4][8] = {
  {
    "OSC1",
    "FM/RM",
    "WS",
    "Uni",
    "Harm",
    "Gran",
    "Filter",
    "Env"
  },
  {
    "OSC2",
    "FM/RM",
    "WS",
    "Uni",
    "Harm",
    "Gran",
    "Filter",
    "Env"
  },
  {
    "LFO 1-4",
    "Mod 1-4",
    "Mod 5-8",
    "",
    "",
    "",
    "",
    ""
  },
  {
    "FX 1",
    "FX 2",
    "FX 3",
    "FX 4",
    "",
    "",
    "",
    ""
  },
};
void controlChange(byte channel, byte control, byte value) {
  midiEventPacket_t event = {0x0B, (uint8_t)(0xB0 | channel), control, value};
  MidiUSB.sendMIDI(event);
  MidiUSB.flush();
}

void programChange(byte channel, byte program) {
  Serial.print("Program change ");
  Serial.print(program);
  Serial.print(" on channel ");
  Serial.println(channel);
  midiEventPacket_t event = {0x0C, (uint8_t)(0xC0 | channel), program, 0};
  MidiUSB.sendMIDI(event);
  MidiUSB.flush();
}

int encoder_val[NUM_ENCODER] = {0, 5};
int encoder_state[NUM_ENCODER] = {0};

bool mixer_mode = false;
int encoder_stored_device[16];
int encoder_stored_mixer[16];

static void mirror_slot_to_storage(int idx) {
  if (idx < 0 || idx > 15) return;
  if (mixer_mode) {
    encoder_stored_mixer[idx] = encoder_val[idx];
  } else {
    encoder_stored_device[idx] = encoder_val[idx];
  }
}

static void send_slot_cc(uint8_t slot, int value) {
  if (slot > 15) return;
  uint8_t cc;
  if (!mixer_mode) {
    cc = CC_DEVICE_ENC0 + slot;
  } else if (slot < 8) {
    cc = CC_MIX_VOL0 + slot;
  } else {
    cc = CC_MIX_PAN0 + (slot - 8);
  }
  controlChange(MIDI_CH_CUBEFISH, cc, (uint8_t)value);
}

uint32_t g_enc_switch_state = 0;
uint32_t g_enc_switch_up = 0;
uint32_t g_enc_switch_down = 0;

int textWidth(String text) {
    // Estimate width of text (based on font size and characters)
    return text.length() * 6; // Rough approximation, 6 pixels per character
}

bool in_ctrl = false;


uint8_t last_two_layers[2] = {0}; // index 0 = oldest


void set_last_two_layers(uint8_t ch) {
  // Same as newest
  if (ch == last_two_layers[1]) {// Same as oldest {
  } else {

    // Push newest to oldest
    last_two_layers[0] = last_two_layers[1];

    // replace newest
    last_two_layers[1] = ch;
  }
}

uint8_t get_prev_layer() {
  return last_two_layers[0];
}


uint8_t num_inactive_global_incr = 0;
void write(Adafruit_SSD1306* display, String text, uint8_t x, uint8_t y, uint8_t width) {
    int lineHeight = 8; // Set based on text size
    String word = "";
    String line = "";

    display->setCursor(x, y);

    for (unsigned int i = 0; i < text.length(); i++) {
        char c = text[i];
        if (c == ' ' || c == '\n') {
            if (textWidth(line + word) > width) {
                display->println(line);
                line = "";
                y += lineHeight;
                display->setCursor(x, y);
            }
            line += word + ' ';
            word = "";
        } else {
            word += c;
        }
    }
    if (textWidth(line + word) > width) {
        display->println(line);
        y += lineHeight;
        display->setCursor(x, y);
        line = "";
    }
    display->println(line + word);
}


void update_button_display(uint8_t button_display_num, uint32_t switch_state) {
    cur_display = set_display(button_display_num + 16);
    cur_display->clearDisplay();

    uint8_t left_idx = button_display_num * 2;
    uint8_t right_idx = button_display_num * 2 + 1;

    char* left = button_text[left_idx];
    char* right = button_text[right_idx];

    bool l_on = switch_state & (shifter << (17 + left_idx));
    bool r_on = switch_state & (shifter << (17 + right_idx));

  //   if (sw_down || sw_up) {
  //     uint8_t display_num = 16 + (idx - 17) / 2; // 16 - 20
  //     uint8_t pos = (idx - 1) % 2; // left or right
  //     cur_display = set_display(display_num % 20);
  //     cur_display->clearDisplay();
  //     if (cur_on) {
  //       cur_display->setCursor(0, 0);
  //       cur_display->fillRect(pos * 64, 0, 64, 32, 1);
  //       controlChange(1, 50 + idx - 17, 127);
  //     } 
  //     // else {
  //     //   controlChange(1, 50 + idx - 17, 0);
  //     // }
  //     cur_display->display();
  //   }
    cur_display->drawLine(63, 0, 63, 31, 1);
    
    // if (l_on) {
    //   cur_display->setCursor(0, 0);
    //   cur_display->fillRect(0, 0, 63, 32, 1);
    // }
    if (in_ctrl) {
        cur_display->setCursor(0, 16);
        cur_display->setTextSize(1);

        // if (l_on) {
        //   cur_display->fillRect(0, 0, 64, 32, 1);
        // } else {

          if (left_idx <= 3) {

            String left_str = channel_names[left_idx];
            if (left_idx + 1 == cur_channel || l_on) {
              left_str += " [*]";
            }
            write(cur_display, left_str, 0, 16, 61);
          } else {
            write(cur_display, String(""), 0, 16, 61);
          }
        // }


        cur_display->setCursor(0, 16);
        cur_display->setTextSize(1);
        // if (r_on) {
        //   cur_display->fillRect(64, 0, 64, 32, 1);
        // } else {
          if (right_idx <= 3) {
            String right_str = channel_names[right_idx];
            if (right_idx + 1 == cur_channel || r_on) {
              right_str += " [*]";
            }
            write(cur_display, right_str, 67, 16, 61);
          } else {
            write(cur_display, String(""), 67, 16, 61);
          }
        // }

    } else {
      // Use script-provided bank names (e.g. Reverb, Delay) when available, else fallback to hardcoded
      cur_display->setCursor(0, 0);
      cur_display->setTextSize(1);

      String left_str = (left[0]) ? String(left) : "";
      if (selected_button == left_idx) {
        left_str += " [*]";
      }
      write(cur_display, left_str, 0, 0, 61);

      String right_str = (right[0]) ? String(right) : "";
      if (selected_button == right_idx) {
        right_str += " [*]";
      }
      write(cur_display, right_str, 67, 0, 61);
    }

    cur_display->display();
}

uint8_t encoder_page = 0;
void loop() {
  uint32_t changed_knobs = 0;
  uint8_t changed_buttons = 0;

  #if ENABLE_MIDI
  midiEventPacket_t rx;
  do {
    rx = MidiUSB.read();
    uint8_t cin = rx.header & 0x0F;
    if (cin >= 4 && cin <= 7) {
      // USB MIDI sysex: append by Code Index — MUST copy 0x00 data bytes (do not use if(byte2)).
      if (rx.byte1 == 0xF0) {
        sysex_index = 0;
      }
      if (sysex_index < SYSEX_BUF_SIZE - 1) {
        sysex_buf[sysex_index++] = rx.byte1;
      }
      if (cin == 0x04) {
        if (sysex_index < SYSEX_BUF_SIZE - 1) sysex_buf[sysex_index++] = rx.byte2;
        if (sysex_index < SYSEX_BUF_SIZE - 1) sysex_buf[sysex_index++] = rx.byte3;
      } else if (cin == 0x05) {
        if (sysex_index < SYSEX_BUF_SIZE - 1) sysex_buf[sysex_index++] = rx.byte2;
      } else if (cin == 0x06) {
        if (sysex_index < SYSEX_BUF_SIZE - 1) sysex_buf[sysex_index++] = rx.byte2;
        if (sysex_index < SYSEX_BUF_SIZE - 1) sysex_buf[sysex_index++] = rx.byte3;
      }
      /* cin 0x07: only byte1 (already stored) */

      if (cin == 7 || cin == 6 || cin == 5) {
        // Process complete sysex message
        int encoder_num = sysex_buf[1] - 1;
        // Serial.print("# Got sysex of len ");
        // Serial.println(sysex_index - 2);
        // for (int i = 2; i < sysex_index - 1; i++) {
        //   Serial.print((char)sysex_buf[i]);
        // }
        // Serial.println("");

        sysex_buf[sysex_index] = 0;
        // sysex_buf[DISPLAY_TEXT_LEN - 1] = 0;
        uint16_t val_len = sysex_index;
        sysex_index = 0;

        if (val_len < 4 || sysex_buf[0] != 0xF0) {
          continue;
        }
        // Knob (1-16): F0, enc, CUBEFISH_KNOB_SYNC_TAG, midi 0-127 or 128=skip, display..., F7
        // Legacy knob: F0, enc, display..., F7 (no tag)
        // Bank labels: F0, 50-57, display..., F7
        if (0 <= encoder_num && encoder_num <= 15) {
          const uint8_t *disp_src;
          uint16_t disp_max;
          if (val_len >= 6 && sysex_buf[2] == CUBEFISH_KNOB_SYNC_TAG) {
            uint8_t midi_sync = sysex_buf[3];
            disp_src = sysex_buf + 4;
            disp_max = (val_len > 5) ? (val_len - 5) : 0; /* excludes F0,enc,tag,midi,F7 */
            if (midi_sync <= 127) {
              last_recv_encoder_val[encoder_num] = (int)midi_sync;
#if LOG_ABLETON_MIDI
              Serial.print(F("[AB] rx enc="));
              Serial.print(encoder_num);
              Serial.print(F(" midi="));
              Serial.print(midi_sync);
              Serial.print(F(" sysex_len="));
              Serial.println(val_len);
#endif
            } else {
#if LOG_ABLETON_MIDI
              Serial.print(F("[AB] rx enc="));
              Serial.print(encoder_num);
              Serial.print(F(" sync=SKIP sysex_len="));
              Serial.println(val_len);
#endif
            }
          } else {
            /* Legacy: infer sync from display text (fragile) */
            disp_src = sysex_buf + 2;
            disp_max = (val_len > 3) ? (val_len - 3) : 0;
            int parsed_val = -1;
            int value_start = 2;
            for (int i = 2; i < val_len - 1; i++) {
              if (sysex_buf[i] == '\n') {
                value_start = i + 1;
                break;
              }
            }
            for (int i = value_start; i < val_len - 1; i++) {
              if (sysex_buf[i] >= '0' && sysex_buf[i] <= '9') {
                parsed_val = 0;
                while (i < val_len - 1 && sysex_buf[i] >= '0' && sysex_buf[i] <= '9') {
                  parsed_val = parsed_val * 10 + (sysex_buf[i] - '0');
                  if (parsed_val > 127) parsed_val = 127;
                  i++;
                }
                break;
              }
            }
            if (parsed_val >= 0) {
              last_recv_encoder_val[encoder_num] = parsed_val;
#if LOG_ABLETON_MIDI
              Serial.print(F("[AB] rx LEGACY enc="));
              Serial.print(encoder_num);
              Serial.print(F(" parsed="));
              Serial.print(parsed_val);
              Serial.print(F(" sysex_len="));
              Serial.println(val_len);
#endif
            }
#if LOG_ABLETON_MIDI
            else {
              Serial.print(F("[AB] rx LEGACY enc="));
              Serial.print(encoder_num);
              Serial.print(F(" no_parse sysex_len="));
              Serial.println(val_len);
            }
#endif
          }
          uint8_t copy_len = (disp_max < DISPLAY_TEXT_LEN - 1) ? (uint8_t)disp_max : (DISPLAY_TEXT_LEN - 1);
          memcpy(display_text[encoder_num], disp_src, copy_len);
          display_text[encoder_num][copy_len] = 0;
          changed_knobs |= shifter << encoder_num;
        } else if (50 <= encoder_num + 1 && encoder_num + 1 <= 57) {
          uint8_t button_num = encoder_num + 1 - 50;
          uint16_t payload_len = (val_len > 3) ? (val_len - 3) : 0;
          uint8_t copy_len = (payload_len < DISPLAY_TEXT_LEN - 1) ? payload_len : (DISPLAY_TEXT_LEN - 1);
          memcpy(button_text[button_num], sysex_buf + 2, copy_len);
          button_text[button_num][copy_len] = 0;
          changed_buttons |= shifter << button_num;
        } else {
          // Ignore sysex from other devices (e.g. Novation) - not from cubefish
        }

      }
    }

    // if (rx.header == 0x0B) {
    //   int channel = rx.byte2 - 20;
    //   if (channel >= 0 && channel <= 15) {
    //     Serial.print("Setting counter for ");
    //     Serial.print(channel);
    //     Serial.print(" to ");
    //     Serial.println(rx.byte3);
    //     encoder_val[channel] = rx.byte3;
    //     changed_knobs |= shifter << channel;
    //   }
    // }
  } while (rx.header != 0);
  #endif


  int cur_states[NUM_ENCODER] = {0};
  noInterrupts();
  for (int i = 0; i < NUM_ENCODER; i++) {
      cur_states[i] = encoder_state[i];
      encoder_state[i] = 0;
  }
  uint32_t switch_state = update_encoder_switch_state();
  
  interrupts();

  // Update encoder values
  for (int idx = 0; idx < 17; idx++) {
    int incr = cur_states[idx];

    bool sw_down = g_enc_switch_down & (shifter << idx);
    bool sw_up = g_enc_switch_up & (shifter << idx);
    if (incr || sw_down || sw_up) {
      if (idx == 16) {
        if (sw_down) {
          if (mixer_mode) {
            memcpy(encoder_stored_mixer, encoder_val, sizeof(int) * 16);
            memcpy(encoder_val, encoder_stored_device, sizeof(int) * 16);
            mixer_mode = false;
          } else {
            memcpy(encoder_stored_device, encoder_val, sizeof(int) * 16);
            memcpy(encoder_val, encoder_stored_mixer, sizeof(int) * 16);
            mixer_mode = true;
          }
          in_ctrl = false;
          for (int j = 0; j < 16; j++) {
            last_recv_encoder_val[j] = -1;
          }
          changed_knobs |= 0xFFFFu;
          controlChange(MIDI_CH_CUBEFISH, CC_MIX_MODE_TOGGLE, 127);
          for (int s = 0; s < 16; s++) {
            send_slot_cc((uint8_t)s, encoder_val[s]);
          }
        }
        if (!mixer_mode && incr && num_inactive_global_incr == 10) {
          // toggle bank and layer
          Serial.println("Toggling prev layer");
          uint8_t new_ch = get_prev_layer();
          if (new_ch) {

            // Changing channel
            cur_channel = new_ch;
            changed_buttons = 0b11111111;
            controlChange(0, 127, cur_channel);

            // Changing bank
            selected_button = layer_to_selected_bank[cur_channel - 1];
            encoder_page = selected_button;
            Serial.print("Sending bank button ");
            Serial.println(selected_button);
            controlChange(2, 50 + selected_button, 127);

            set_last_two_layers(cur_channel);
          }
          num_inactive_global_incr = 0;
        }

        continue;
      }
      encoder_val[idx] += incr;

      if (encoder_val[idx] < 0) {
        encoder_val[idx] = 0;
      } else if (encoder_val[idx] > 127) {
        encoder_val[idx] = 127;
      }

      // Toggle between 0 and 127 (device mode only; mixer uses continuous volume/pan)
      if (!mixer_mode && sw_down) {
        if (encoder_val[idx] < 64) {
          encoder_val[idx] = 127;
        } else {
          encoder_val[idx] = 0;
        }
      }

      // Serial.print("Ecoder wait ");
      // Serial.println(idx);
      encoder_wait[idx] = 300000;
      changed_knobs |= shifter << idx;
      mirror_slot_to_storage(idx);
      send_slot_cc((uint8_t)idx, encoder_val[idx]);
    }
  }

  for (int i = 0; i < 16; i++) {
    if (encoder_wait[i] > 0) {
      encoder_wait[i] -= 1;
      // if (encoder_wait[i] == 0) {
      //   Serial.print("Ecoder done wait ");
      //   Serial.println(i);
      // }
    }
  }
  for (int i = 0; i < 16; i++) {
    if (last_recv_encoder_val[i] >= 0 && encoder_wait[i] == 0) {
      encoder_val[i] = last_recv_encoder_val[i];
#if LOG_ABLETON_MIDI
      Serial.print(F("[AB] apply enc="));
      Serial.print(i);
      Serial.print(F(" val="));
      Serial.println(encoder_val[i]);
#else
      Serial.print("Updating encoder ");
      Serial.print(i);
      Serial.print(" to ");
      Serial.println(encoder_val[i]);
#endif
      last_recv_encoder_val[i] = -1;
      mirror_slot_to_storage(i);
    }
  }

  if (num_inactive_global_incr < 10) {
    num_inactive_global_incr += 1;
  }

  // Encoder displays
  for (int idx = 0; idx < 16; idx++) {
    if ((changed_knobs >> idx) & 1) {
      update_encoder_display(idx);
    }
  }

  // if (changed_buttons) {
  //   selected_button = 0;
  // }

  // Button events (bank / layer UI — not used while in mixer mode)
  if (!mixer_mode)
  for (uint8_t button_num = 0; button_num < 9; button_num++) {
    uint8_t switch_idx;
    if (button_num == 8) { // Ctrl
      switch_idx = 25;
    } else {
      switch_idx = button_num + 17;
    }
    bool sw_down = (g_enc_switch_down >> switch_idx) & 1;
    bool sw_up = (g_enc_switch_up >> switch_idx) & 1;

    if (button_num == 8) { // Ctrl
      if (sw_down) {
        in_ctrl = !in_ctrl;

        changed_buttons = 0b11111111;
      }
    } else {
      if (in_ctrl) {
        if (sw_up) {

          // Changing channel
          cur_channel = button_num + 1;
          changed_buttons = 0b11111111;
          in_ctrl = !in_ctrl;
          controlChange(0, 127, cur_channel);

          // Changing bank
          selected_button = layer_to_selected_bank[cur_channel - 1];
          encoder_page = selected_button;
          Serial.print("Sending bank button ");
          Serial.println(selected_button);
          controlChange(2, 50 + selected_button, 127);

          set_last_two_layers(cur_channel);
        } else if (sw_down) {
          changed_buttons = 0b11111111;
        }
      } else {
        if (sw_down) {

        bool wrapped = true;
        if (wrapped) {
          encoder_page = button_num;
        }
        changed_buttons |= 1 << button_num;
        Serial.print("Sending bank button ");
        Serial.println(button_num);
        controlChange(2, 50 + button_num, 127);
        if (selected_button != button_num) {
          changed_buttons |= 1 << selected_button;
          selected_button = button_num;
        }
        layer_to_selected_bank[cur_channel - 1] = selected_button;
          set_last_two_layers(cur_channel);
        }

      }

    }
  }

  // Button displays (name)
  for (uint8_t button_num = 0; button_num < 8; button_num++) {  
    if ((changed_buttons >> button_num) & 1) {
      update_button_display(button_num / 2, switch_state);
    }

  }

  // cur_display = set_display(16);
  // cur_display->clearDisplay();
  // cur_display->setCursor(0, 0);
  // cur_display->setTextSize(1);
  // cur_display->println(elapsedTime);
  // cur_display->display();
}

void update_encoder_display(int encoder_num) {
  cur_display = set_display(encoder_num);

  cur_display->clearDisplay();
  cur_display->setTextSize(1);
  cur_display->setCursor(0, 0);

  if (display_text[encoder_num][0] == 10 || display_text[encoder_num][0] == 32) {
    cur_display->display();
    return;
  }

  cur_display->println(display_text[encoder_num]);

  // Value visual (knob)
  if (encoder_num % 2 == 0 && 0) {

    cur_display->setCursor(0, 0);
    int radius = 9;
    int centerX = 63;
    int centerY = 22;
    cur_display->drawCircle(centerX, centerY, radius, 1);

    int value = encoder_val[encoder_num];
    // Map the value (0-127) to an angle (0-360 degrees)
    // float angle = map(value, 0, 127, 0, 360);
    // float radians = angle * (PI / 180);

    // // Calculate the end point of the radius line
    // int endX = centerX + radius * cos(radians);
    // int endY = centerY + radius * sin(radians);

    // // Draw the radius line
    // cur_display->drawLine(centerX, centerY, endX, endY, 1);

    // Map the value (0-127) to an angle (135 to -135 degrees)
    float angle = map(value, 0, 127, 135, -135);
    float radians = angle * (PI / 180);

    // Calculate the end point of the radius line
    int endX = centerX - radius * sin(radians);
    int endY = centerY - radius * cos(radians);

    // Draw the radius line
    cur_display->drawLine(centerX, centerY, endX, endY, 1);

  } else {
    // Value visual (rectangle)
    if (encoder_num % 2 && 0) {
      int diff = 64 - encoder_val[encoder_num];
      cur_display->fillRect(0, 28 - 3, 128, 3, 0);
      if (diff > 0) {
        cur_display->fillRect(64 - diff, 28 - 3, diff, 3, 1);
      } else {
        cur_display->fillRect(64, 28 - 3, -1 * diff, 3, 1);
      }
      cur_display->fillRect(63, 28 - 3 - 2, 2, 7, 1);
    } else {
      cur_display->fillRect(0, 28 - 3, 128, 3, 0);
      cur_display->fillRect(0, 28 - 3 - 1, 1, 5, 1); // left bar for 0
      cur_display->fillRect(0, 28 - 3, encoder_val[encoder_num], 3, 1);
    }

  }
  cur_display->display();
}

// ISR(TIMER1_COMPA_vect) {
//   // unsigned long startTime, endTime, elapsedTime;
//   // startTime = micros();
//   scan_encoders_and_buttons();
//   // endTime = micros();
//   // elapsedTime = endTime - startTime;
// }
void scan_isr() {
    // Clear the interrupt flag at the beginning of the ISR
    startTime = micros();
    scan_encoders_and_buttons();
    endTime = micros();
    elapsedTime = endTime - startTime;
}

int8_t encoder_cha_state_prev[NUM_ENCODER] = {0};
int8_t encoder_chb_state_prev[NUM_ENCODER] = {0};
uint16_t encoder_inactive_counter[NUM_ENCODER] = {0};
uint16_t encoder_event_cycle_counts[NUM_ENCODER] = {0};
int8_t encoder_last_movement[NUM_ENCODER] = {0};

uint32_t enc_switch_debounce_buffer[SWITCH_DEBOUNCE_BUFFER_SIZE] = {0};
uint32_t g_enc_prev_switch_state = 0;
uint8_t enc_switch_buffer_pos = 0;
/**
 * Scans the encoder switch registers and returns the de-bounced 
 * enc_switch_state global variable.
 */
uint32_t update_encoder_switch_state(void)
{
    // De-bounce the encoder switch's by ORing the columns of the buffer
    // Any switch down even is immediately recognized, however it will take 10 samples
    // for a switch design to be recognized
    g_enc_switch_state = 0;
    
    for(uint8_t i=0;i<SWITCH_DEBOUNCE_BUFFER_SIZE;++i) {
      g_enc_switch_state |= enc_switch_debounce_buffer[i];
    }
    
    // If a bit has changed, and it is 1 in the current state, it's a KeyUp.
    g_enc_switch_up = (g_enc_prev_switch_state ^ g_enc_switch_state) & g_enc_prev_switch_state;
    // If a bit has changed and it was 1 in the previous state, it's a KeyDown.
    g_enc_switch_down = (g_enc_prev_switch_state ^ g_enc_switch_state) & g_enc_switch_state;
    // Demote the current state to history.
    g_enc_prev_switch_state = g_enc_switch_state;
    
    return g_enc_switch_state;
}

void scan_encoders_and_buttons() {
  uint8_t cha_states[NUM_ENCODER] = {0};
  uint8_t chb_states[NUM_ENCODER] = {0};
  uint32_t switch_states = 0;
  for (uint8_t mux_ch = 0; mux_ch < 16; ++mux_ch) {
      // Set mux channel
      // PORTF = ((mux_ch >> 2) << 4) | (mux_ch & 0b11);

      digitalWrite(S0_A, mux_ch & 0b1);
      digitalWrite(S1_A, mux_ch & 0b10);
      digitalWrite(S2_A, mux_ch & 0b100);
      digitalWrite(S3_A, mux_ch & 0b1000);

      digitalWrite(S0_B, mux_ch & 0b1);
      digitalWrite(S1_B, mux_ch & 0b10);
      digitalWrite(S2_B, mux_ch & 0b100);
      digitalWrite(S3_B, mux_ch & 0b1000);
      delayMicroseconds(5);

      // uint8_t mux_vals[5] = {
      //   (pinb >> 4) & 1, // L1
      //   (pinb >> 6) & 1, // L2
      //   (pind >> 7) & 1, // U
      //   (pind >> 4) & 1, // R1
      //   (pinc >> 6) & 1, // R2
      // };
      uint8_t mux_vals[5] = {
        digitalRead(SIG_L1), // L1
        digitalRead(SIG_L2), // L2
        digitalRead(SIG_U), // U
        digitalRead(SIG_R1), // R1
        digitalRead(SIG_R2), // R2
      };

      uint8_t (*ch_settings)[5][2] = mux_to_param + mux_ch;
      
      for (uint8_t mux_idx = 0; mux_idx < 5; mux_idx++) {
        uint8_t encoder_num = (*ch_settings)[mux_idx][0];
        uint8_t encoder_ch = (*ch_settings)[mux_idx][1];
        uint8_t val = mux_vals[mux_idx];

        if (encoder_ch == CH_A) {
          cha_states[encoder_num] = val;
        } else if (encoder_ch == CH_B) {
          chb_states[encoder_num] = val;
        }
        else if (encoder_ch == CH_SW && !val) {
          switch_states |= shifter << encoder_num;
        }
      }
  }

	enc_switch_debounce_buffer[enc_switch_buffer_pos] = switch_states;
	enc_switch_buffer_pos = (enc_switch_buffer_pos + 1) % SWITCH_DEBOUNCE_BUFFER_SIZE;
  // g_enc_switch_state = switch_states;
	for (uint8_t i = 0; i < NUM_ENCODER; ++i) {
    uint8_t encoder_cha_state = cha_states[i];
    uint8_t encoder_chb_state = chb_states[i];


		uint8_t this_encoder_state = ((encoder_cha_state) ? 0x04 : 0x00) | ((encoder_chb_state) ? 0x08 : 0x00) |
					 ((encoder_cha_state_prev[i]) ? 0x01 : 0x00) | ((encoder_chb_state_prev[i]) ? 0x02 : 0x00);
		int8_t encoder_action = EncoderActionByState[this_encoder_state]; // Get Encoder Action for current state
		if (encoder_action == 0 || encoder_action <= -127) { // Encoder is Idle
			// TODO: Handle the -127 'ambiguous' state more gracefully (presuming direction by momentum for example)
			if ( encoder_inactive_counter[i] < ENCODER_INACTIVE_THRESHOLD ){ // For determining when an encoder is inactive
				encoder_inactive_counter[i]++;
			}

		} //else if (enocder_action <= -127) { // Encoder is in an ambiguous state
		//} 
		else if (encoder_action < 0) { // Event! Moving CCW
			// encoder event table: mark event type +store event cycle count + increment event counter
      uint16_t cycle_count = encoder_inactive_counter[i] + 1;
      int8_t last_move = encoder_last_movement[i]; 
      if (cycle_count >= ENCODER_DEBOUNCE_CYCLE_TIMEOUT) { // event spacing was reasonable, allow to travel freely in either direction
        // Add event to the tally
        encoder_state[i]--;
        encoder_event_cycle_counts[i] += cycle_count; // cycles for this event to occur.
        encoder_last_movement[i] = -1;
      } else if (last_move == -1) { // Moving fast but in a consistent direction
        // Add event to the tally
        encoder_state[i]--;
        encoder_event_cycle_counts[i] += cycle_count; // cycles for this event to occur.
        //redundant encoder_last_movement[i] = -1;
      } else { // moving fast in a different direction
        // Reject Event, but change direction to allow subsequent events to pass if in same direction
        encoder_last_movement[i] = -1;
      }
      encoder_inactive_counter[i] = 0; // clear the inactive counter for all states
		} else { // Event! Moving CW
			// !mark encoder event table: mark event type +store event cycle count + increment event counter
      uint16_t cycle_count = encoder_inactive_counter[i] + 1;
      int8_t last_move = encoder_last_movement[i];
      if (cycle_count >= ENCODER_DEBOUNCE_CYCLE_TIMEOUT) { // event spacing was reasonable, allow to travel freely in either direction
        // Add event to the tally
        encoder_state[i]++;
        encoder_event_cycle_counts[i] += cycle_count; // cycles for this event to occur.
        encoder_last_movement[i] = 1;
      } else if (last_move == 1) { // Moving fast but in a consistent direction
        // Add event to the tally
        encoder_state[i]++;
        encoder_event_cycle_counts[i] += cycle_count; // cycles for this event to occur.
        //redundant encoder_last_movement[i] = 1;
      } else { // moving fast in a different direction
        // Reject Event, but change direction to allow subsequent events to pass
        encoder_last_movement[i] = 1;
      }
      encoder_inactive_counter[i] = 0; // clear the inactive counter for all states
		}
    // Store current state for future comparisons
    encoder_cha_state_prev[i] = encoder_cha_state;
    encoder_chb_state_prev[i] = encoder_chb_state;
    
	}
}

void setup() {
  for (int i = 0; i < 16; i++) {
    last_recv_encoder_val[i] = -1;
  }

  Serial.begin(9600);
  Serial.println("Setting up");
  TCA_R_WIRE.begin();
  TCA_WIRE.begin();
  init_displays();
  init_mux();
  init_interrupts();
  Serial.println("Done");

  for (uint8_t i = 0; i < 4; i++) {
    update_button_display(i, 0);
  }

  for (int i = 0; i < 16; i++) {
    encoder_stored_device[i] = encoder_val[i];
    encoder_stored_mixer[i] = (i < 8) ? 100 : 64;
  }
}
