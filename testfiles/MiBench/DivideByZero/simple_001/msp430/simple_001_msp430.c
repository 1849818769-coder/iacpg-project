/*
 * DivideByZero - simple_001
 * Architecture: MSP430 (GCC)
 */

#include <stdint.h>

#define __interrupt

void __enable_interrupt(void) {}
void __disable_interrupt(void) {}

int rand(void);
void print(int);

volatile int simple_001_d;

void simple_001_msp430_main(void) {
    simple_001_d = rand();
    if (simple_001_d != 0) {
        print(10 / simple_001_d);
    }
}

#pragma vector = TIMER0_A0_VECTOR
__interrupt void simple_001_msp430_isr_1(void) {
    simple_001_d--;
}

#pragma vector = USCI_A0_VECTOR
__interrupt void simple_001_msp430_isr_2(void) {
    simple_001_d--;
    if (simple_001_d <= 0) {
        simple_001_d = 1;
    }
}
