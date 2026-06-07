/*
 * multiwordDatarace - simple_001
 * Architecture: MSP430 (GCC)
 */

#include <stdint.h>

#define __interrupt

void __enable_interrupt(void) {}
void __disable_interrupt(void) {}

void init(void);
void idlerun(void);

volatile int64_t down_counter_ms = 0;

void simple_001_msp430_main(void) {
    __disable_interrupt();
    init();
    __enable_interrupt();
    down_counter_ms = 500;
    idlerun();
}

#pragma vector = TIMER0_A0_VECTOR
__interrupt void simple_001_msp430_isr_1(void) {
    down_counter_ms = down_counter_ms - 1;
}
