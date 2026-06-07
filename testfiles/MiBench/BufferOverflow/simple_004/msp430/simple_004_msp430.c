/*
 * BufferOverflow - simple_004
 * Architecture: MSP430 (GCC)
 */

#include <stdint.h>

#define __interrupt

void __enable_interrupt(void) {}
void __disable_interrupt(void) {}

#define BUFFER_SIZE 10
typedef unsigned int uint;
int simple_004_global_array[BUFFER_SIZE];

void simple_004_msp430_main(void) {
  for (uint i = 0; i < BUFFER_SIZE; i++) {
    if (simple_004_global_array[i] == 0) {
      return;
    }
  }
}

#pragma vector = TIMER0_A0_VECTOR
__interrupt void simple_004_msp430_isr(void) {
  for (uint i = 0; i < BUFFER_SIZE; i++) {
    simple_004_global_array[i] = 0;
  }
}
