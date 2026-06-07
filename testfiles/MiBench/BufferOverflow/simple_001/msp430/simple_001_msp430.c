/*
 * BufferOverflow - simple_001
 * Architecture: MSP430 (GCC)
 */

#include <stdint.h>

#define __interrupt

void __enable_interrupt(void) {}
void __disable_interrupt(void) {}

#define BUFFER_SIZE 10
int simple_001_global_array[BUFFER_SIZE];
unsigned int simple_001_global_var;
void simple_001_Init(void);

void simple_001_msp430_main(void) {
  simple_001_Init();
  if(simple_001_global_var < BUFFER_SIZE){
    simple_001_global_array[simple_001_global_var] = 0;
  }
}

void simple_001_Init(void) {
  simple_001_global_var = 1;
}

#pragma vector = TIMER0_A0_VECTOR
__interrupt void simple_001_msp430_isr(void) {
  simple_001_global_var = 0;
  simple_001_global_var = BUFFER_SIZE + 1;
}
