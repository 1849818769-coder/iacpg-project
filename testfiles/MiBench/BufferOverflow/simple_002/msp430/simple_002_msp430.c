/*
 * BufferOverflow - simple_002
 * Architecture: MSP430 (GCC)
 */

#include <stdint.h>

#define __interrupt

void __enable_interrupt(void) {}
void __disable_interrupt(void) {}

#define BUFFER_SIZE 10
typedef unsigned int uint;
int simple_002_global_array[BUFFER_SIZE];
uint simple_002_global_var1;
uint simple_002_global_var2;
void simple_002_Init(void);
int rand(void);

void simple_002_msp430_main(void) {
  simple_002_Init();
  if (simple_002_global_var1 < BUFFER_SIZE &&
      simple_002_global_var2 < BUFFER_SIZE) {
    simple_002_global_array[simple_002_global_var1] = 0;
    simple_002_global_array[simple_002_global_var2] = 0;
  }
}

void simple_002_Init(void) {
  simple_002_global_var1 = 0;
  simple_002_global_var2 = 0;
}

#pragma vector = TIMER0_A0_VECTOR
__interrupt void simple_002_msp430_isr(void) {
  for (uint i = 0; i < BUFFER_SIZE; i++) {
    simple_002_global_var1 = 0;
    simple_002_global_var2 = rand();
  }
}
