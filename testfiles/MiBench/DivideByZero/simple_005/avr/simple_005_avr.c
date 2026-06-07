/*
 * DivideByZero - simple_005 (hard)
 * Architecture: AVR
 */

#include "../../common.h"

#define ISR(vector) void vector(void)

void sei(void) {}
void cli(void) {}
void print(int);

volatile int raw_divisor;

static int get_divisor(void) { return raw_divisor; }

void simple_005_avr_main(void) {
    init();
    sei();

    raw_divisor = 10;

    if (raw_divisor != 0) {
        int d = get_divisor();
        print(100 / d);
    }
}

ISR(TIMER1_OVF_vect) {
    raw_divisor = 0;
}
