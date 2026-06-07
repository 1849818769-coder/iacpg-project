/*
 * BufferOverflow - simple_006 (hard, TN)
 * Architecture: MSP430
 */

#include "../../common.h"

#define __interrupt

void __enable_interrupt(void) {}
void __disable_interrupt(void) {}

#define BUFFER_SIZE 10
int buffer[BUFFER_SIZE];
volatile unsigned int idx;

void simple_006_msp430_main(void) {
    init();
    __enable_interrupt();

    __disable_interrupt();
    if (idx < BUFFER_SIZE) {
        buffer[idx] = 99;
    }
    __enable_interrupt();
}

__interrupt void TIMER0_A0_ISR(void) {
    idx = BUFFER_SIZE + 1;
}
