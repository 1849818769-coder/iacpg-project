/*
 * BufferOverflow - simple_003
 * Architecture: AVR (avr-libc)
 */

#include <stdint.h>

#define ISR(vector) void vector(void)

void sei(void) {}
void cli(void) {}

#define BUFFER_SIZE 10
typedef unsigned int uint;
typedef unsigned char uchar;
int simple_003_global_array[BUFFER_SIZE];
uchar simple_003_global_flag = 0;
uint simple_003_global_var1;
uint simple_003_global_var2;
void simple_003_Init(void);
void simple_003_Adjust(void);
int rand(void);

void simple_003_avr_main(void) {
  simple_003_Init();
  sei();
  simple_003_Adjust();
  simple_003_global_array[simple_003_global_var1] = 0;
  simple_003_global_array[simple_003_global_var2] = 0;
}

void simple_003_Init(void) {
  simple_003_global_flag = 0;
  simple_003_global_var1 = 0;
  simple_003_global_var2 = 0;
}

void simple_003_Adjust(void) {
  if(simple_003_global_flag){
    simple_003_global_var1 = rand() % BUFFER_SIZE;
    simple_003_global_flag = 0;
  }else{
    simple_003_global_var1 = rand() % BUFFER_SIZE;
  }
}

ISR(TIM2_vect) {
  simple_003_global_flag = 1;
  simple_003_global_var1 = BUFFER_SIZE + 5;
}
