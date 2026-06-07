/*
 * DivideByZero - simple_006 (hard)
 * Architecture: MSP430
 */

#include "../../common.h"

#define __interrupt

void __enable_interrupt(void) {}
void __disable_interrupt(void) {}
void print(int);

volatile int divisor;
volatile int safe_flag;

void simple_006_msp430_main(void) {
    init();
    __enable_interrupt();

    divisor = 10;
    safe_flag = 1;

    if (safe_flag) {
        __disable_interrupt();
    }

    if (divisor != 0) {
        print(100 / divisor);
    }

    if (safe_flag) {
        __enable_interrupt();
    }
}

__interrupt void TIMER0_A0_ISR(void) {
    safe_flag = 0;
    divisor = 0;
}
