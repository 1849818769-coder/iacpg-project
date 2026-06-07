/*
 * multiwordDatarace - simple_002
 * Architecture: MSP430 (GCC)
 */

#include <stdint.h>

#define __interrupt

void __enable_interrupt(void) {}
void __disable_interrupt(void) {}

void init(void);
void idlerun(void);

volatile uint64_t curr_sec = 0;
volatile uint32_t sec_high = 1;
volatile uint32_t sec_low = 2;
volatile uint64_t front_sec = 0;

void simple_002_msp430_main(void) {
    init();
    idlerun();
    front_sec = curr_sec;
}

#pragma vector = TIMER0_A0_VECTOR
__interrupt void simple_002_msp430_isr_1(void) {
    curr_sec = ((uint64_t)sec_high << 32) | sec_low;
}
