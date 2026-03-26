
/* MIDI */
#define ENABLE_MIDI 1

/* Cubefish + Live (cubefish/Arduino.py): channel 15 */
#define MIDI_CH_CUBEFISH 15
#define CC_DEVICE_ENC0 20
#define CC_MIX_VOL0 40
#define CC_MIX_PAN0 48
#define CC_CLIP_ENC0 60
/* Knob SysEx 2nd byte: 1–16=device, 17–32=mixer, 33–48=clip. Must match cubefish/encoder.py */
#define SYSEX_ENC_DEVICE_LO 1
#define SYSEX_ENC_DEVICE_HI 16
#define SYSEX_ENC_MIXER_LO 17
#define SYSEX_ENC_MIXER_HI 32
#define SYSEX_ENC_CLIP_LO 33
#define SYSEX_ENC_CLIP_HI 48

/* Encoder/Button */
#define NUM_ENCODER 17
#define NUM_SWITCH 26
// Encoder channels
#define CH_NONE
#define CH_A 1 // top pin
#define CH_B 2
#define CH_SW 3

#define S3_A 4
#define S2_A 5
#define S1_A 6
#define S0_A 7

#define S3_B 15
#define S2_B 14
#define S1_B 13
#define S0_B 41

#define SIG_L2 2
#define SIG_L1 1
#define SIG_U 3
#define SIG_R2 20
#define SIG_R1 19

#define SCAN_PER_SEC 2000
#define SWITCH_DEBOUNCE_BUFFER_SIZE 20
#define ENCODER_INACTIVE_THRESHOLD 100
#define ENCODER_DEBOUNCE_CYCLE_TIMEOUT 25

const int8_t EncoderActionByState[16] = {	
	0, -1, 1, -127,
	1, 0, -127, -1,
	-1, -127, 0, 1,
	-127, 1, -1, 0
};
/*
Encoder nums

25       16
17 18 19 20 21 22 23 24
-----------
0    1    2    3
4    5    6    7
8    9    10   11
12   13   14   15
*/
// mux channel => mux num => encoder num, encoder ch





uint8_t mux_to_param[16][5][2] = {
  // L1 | L2 | U | R1 | R2
  {{1, CH_A}, {9, CH_A}, {24, CH_SW}, {6, CH_SW}, {14, CH_SW}},
  {{1, CH_B}, {9, CH_B}, {23, CH_SW}, {6, CH_B}, {14, CH_B}},
  {{1, CH_SW}, {9, CH_SW}, {22, CH_SW}, {6, CH_A}, {14, CH_A}},
  {{0, CH_A}, {8, CH_A}, {21, CH_SW}, {7, CH_SW}, {15, CH_SW}},
  {{0, CH_B}, {8, CH_B}, {20, CH_SW}, {7, CH_B}, {15, CH_B}},
  {{0, CH_SW}, {8, CH_SW}, {19, CH_SW}, {7, CH_A}, {15, CH_A}},
  {{4, CH_A}, {12, CH_A}, {18, CH_SW}, {0, CH_NONE}, {0, CH_NONE}},
  {{4, CH_B}, {12, CH_B}, {17, CH_SW}, {16, CH_SW}, {0, CH_NONE}},
  {{4, CH_SW}, {0, CH_NONE}, {25, CH_SW}, {16, CH_B}, {0, CH_NONE}},
  {{0, CH_NONE}, {12, CH_SW}, {0, CH_NONE}, {16, CH_A}, {0, CH_NONE}},
  {{0, CH_NONE}, {0, CH_NONE}, {0, CH_NONE}, {2, CH_SW}, {11, CH_SW}},
  {{0, CH_NONE}, {0, CH_NONE}, {0, CH_NONE}, {2, CH_B}, {11, CH_B}},
  {{0, CH_NONE}, {0, CH_NONE}, {0, CH_NONE}, {2, CH_A}, {11, CH_A}},
  {{5, CH_A}, {13, CH_A}, {0, CH_NONE}, {3, CH_SW}, {10, CH_SW}},
  {{5, CH_B}, {13, CH_B}, {0, CH_NONE}, {3, CH_B}, {10, CH_B}},
  {{5, CH_SW}, {13, CH_SW}, {0, CH_NONE}, {3, CH_A}, {10, CH_A}},
};

/* Display */
#define DISPLAY_TEXT_LEN 50
#define TCA_L 0x70
#define TCA_U 0x71
#define TCA_R 0x72
uint8_t display_map[20][2] = { // display number => TCA address, channel
  {TCA_L, 6},
  {TCA_L, 7},
  {TCA_R, 3},
  {TCA_R, 2},
  {TCA_L, 4},
  {TCA_L, 5},
  {TCA_R, 4},
  {TCA_R, 5},
  {TCA_L, 3},
  {TCA_L, 2},
  {TCA_R, 6},
  {TCA_R, 7},
  {TCA_L, 1},
  {TCA_L, 0},
  {TCA_R, 0},
  {TCA_R, 1},
  {TCA_U, 1},
  {TCA_U, 2},
  {TCA_U, 3},
  {TCA_U, 4},
};

uint32_t shifter = 1;