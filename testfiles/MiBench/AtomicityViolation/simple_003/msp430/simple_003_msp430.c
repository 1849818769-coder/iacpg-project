#include "../../common.h"

#define __interrupt

void __enable_interrupt(void) {}
void __disable_interrupt(void) {}

volatile int svp_simple_008_001_global_var;
volatile int svp_simple_008_001_global_array[100];
volatile int svp_simple_008_001_global_out = 0;

void svp_simple_008_001_func_1();

void svp_simple_008_001_main() {
  init();
  __enable_interrupt();

  int p = 1;
  int q = 2;

  svp_simple_008_001_global_array[p + q] = 0x09;
  svp_simple_008_001_global_array[40] = 0x01;

  svp_simple_008_001_func_1();
}

void svp_simple_008_001_func_1() {
  int reader1, reader2;
  int i = 1;
  int j = 2;
  int p = 1;
  int q = 3;

  reader1 = svp_simple_008_001_global_array[i * 20 + j * 10];
  reader2 = svp_simple_008_001_global_array[p + q];

  /* Use the readers: ISR may overwrite array between main's writes and
     func_1's reads, causing unexpected values (W-W-R atomicity violation) */
  svp_simple_008_001_global_out = reader1 + reader2;
}

__interrupt void TIMER0_A0_ISR(void) {
  int k;
  for (k = 0; k < 100; k++)
    svp_simple_008_001_global_array[k] = 0x05;
}
