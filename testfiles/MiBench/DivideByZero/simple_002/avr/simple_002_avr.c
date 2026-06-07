/*
 * DivideByZero - simple_002
 * Architecture: AVR (avr-libc)
 */

#include <stdint.h>

#define ISR(vector) void vector(void)

void sei(void) {}
void cli(void) {}

int rand(void);

volatile int simple_002_x, simple_002_y, simple_002_z;

void simple_002_avr_main(void) {
    simple_002_x = rand();
    simple_002_y = rand();
    if (simple_002_x < simple_002_y) {
        simple_002_z = 1 / (simple_002_x - simple_002_y);
    }
}

ISR(TIM2_vect) {
    simple_002_x++;
    simple_002_y--;
}

ISR(USART1_vect) {
    simple_002_x++;
    simple_002_y--;
    if (simple_002_x == simple_002_y) {
        simple_002_x++;
        simple_002_y--;
    }
}
