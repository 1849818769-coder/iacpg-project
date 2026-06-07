/*
 * multiwordDatarace - simple_004
 * Architecture: MSP430 (GCC)
 */

#include <stdint.h>

#define __interrupt

void __enable_interrupt(void) {}
void __disable_interrupt(void) {}

void init(void);
void idlerun(void);

volatile uint64_t sequ = 0;
volatile unsigned char packet[4];

void simple_004_msp430_main(void) {
    init();
    packet[0] = (unsigned char)(sequ & 0xffU);
    idlerun();
}

#pragma vector = TIMER0_A0_VECTOR
__interrupt void simple_004_msp430_isr_1(void) {
    sequ = sequ + 1;
}

#pragma vector = USCI_A0_VECTOR
__interrupt void simple_004_msp430_isr_2(void) {
    sequ = sequ + 1;
}
