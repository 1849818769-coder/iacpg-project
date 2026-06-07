/*
 * BufferOverflow - simple_005 (hard)
 * Architecture: MSP430
 */

#include "../../common.h"

#define __interrupt

void __enable_interrupt(void) {}
void __disable_interrupt(void) {}

#define BUFFER_SIZE 10
int buffer[BUFFER_SIZE];
volatile unsigned int index_val;

void simple_005_msp430_main(void) {
    init();

    __disable_interrupt();
    index_val = 0;
    __enable_interrupt();

    if (index_val < BUFFER_SIZE) {
        buffer[index_val] = 42;
    }
}

__interrupt void TIMER0_A0_ISR(void) {
    index_val = BUFFER_SIZE + 5;
}
