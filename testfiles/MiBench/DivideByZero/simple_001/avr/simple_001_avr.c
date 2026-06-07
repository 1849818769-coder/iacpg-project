/*
 * DivideByZero - simple_001
 * Architecture: AVR (avr-libc)
 */

#include <stdint.h>

#define ISR(vector) void vector(void)

void sei(void) {}
void cli(void) {}

int rand(void);
void print(int);

volatile int simple_001_d;

void simple_001_avr_main(void) {
    simple_001_d = rand();
    if (simple_001_d != 0) {
        print(10 / simple_001_d);
    }
}

ISR(TIM2_vect) {
    simple_001_d--;
}

ISR(USART1_vect) {
    simple_001_d--;
    if (simple_001_d <= 0) {
        simple_001_d = 1;
    }
}
