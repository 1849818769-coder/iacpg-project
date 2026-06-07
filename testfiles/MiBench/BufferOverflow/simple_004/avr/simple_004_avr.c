/*
 * BufferOverflow - simple_004
 * Architecture: AVR (avr-libc)
 */

#include <stdint.h>

#define ISR(vector) void vector(void)

void sei(void) {}
void cli(void) {}

#define BUFFER_SIZE 10
typedef unsigned int uint;
int simple_004_global_array[BUFFER_SIZE];

void simple_004_avr_main(void) {
  for (uint i = 0; i < BUFFER_SIZE; i++) {
    if (simple_004_global_array[i] == 0) {
      return;
    }
  }
}

ISR(TIM2_vect) {
  for (uint i = 0; i < BUFFER_SIZE; i++) {
    simple_004_global_array[i] = 0;
  }
}
