/*
 * BufferOverflow - simple_001
 * Architecture: AVR (avr-libc)
 */

#include <stdint.h>

#define ISR(vector) void vector(void)

void sei(void) {}
void cli(void) {}

#define BUFFER_SIZE 10
int simple_001_global_array[BUFFER_SIZE];
unsigned int simple_001_global_var;
void simple_001_Init(void);

void simple_001_avr_main(void) {
  simple_001_Init();
  if(simple_001_global_var < BUFFER_SIZE){
    simple_001_global_array[simple_001_global_var] = 0;
  }
}

void simple_001_Init(void) {
  simple_001_global_var = 1;
}

ISR(TIM2_vect) {
  simple_001_global_var = 0;
  simple_001_global_var = BUFFER_SIZE + 1;
}
