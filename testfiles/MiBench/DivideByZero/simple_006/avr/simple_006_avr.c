/*
 * DivideByZero - simple_006 (hard)
 * Architecture: AVR
 */

#include "../../common.h"

#define ISR(vector) void vector(void)

void sei(void) {}
void cli(void) {}
void print(int);

volatile int divisor;
volatile int safe_flag;

void simple_006_avr_main(void) {
    init();
    sei();

    divisor = 10;
    safe_flag = 1;

    if (safe_flag) {
        cli();
    }

    if (divisor != 0) {
        print(100 / divisor);
    }

    if (safe_flag) {
        sei();
    }
}

ISR(TIMER1_OVF_vect) {
    safe_flag = 0;
    divisor = 0;
}
