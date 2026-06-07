/*
 * DivideByZero - simple_005 (hard)
 * Architecture: MSP430
 */

#include "../../common.h"

#define __interrupt

void __enable_interrupt(void) {}
void __disable_interrupt(void) {}
void print(int);

volatile int raw_divisor;

static int get_divisor(void) { return raw_divisor; }

void simple_005_msp430_main(void) {
    init();
    __enable_interrupt();

    raw_divisor = 10;

    if (raw_divisor != 0) {
        int d = get_divisor();
        print(100 / d);
    }
}

__interrupt void TIMER0_A0_ISR(void) {
    raw_divisor = 0;
}
