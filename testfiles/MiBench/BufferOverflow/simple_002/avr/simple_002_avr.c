/*
 * BufferOverflow - simple_002
 * Architecture: AVR (avr-libc)
 */

#include <stdint.h>

#define ISR(vector) void vector(void)

void sei(void) {}
void cli(void) {}

#define BUFFER_SIZE 10
typedef unsigned int uint;
int simple_002_global_array[BUFFER_SIZE];
uint simple_002_global_var1;
uint simple_002_global_var2;
void simple_002_Init(void);
int rand(void);

void simple_002_avr_main(void) {
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

ISR(TIM2_vect) {
  for (uint i = 0; i < BUFFER_SIZE; i++) {
    simple_002_global_var1 = 0;
    simple_002_global_var2 = rand();
  }
}
