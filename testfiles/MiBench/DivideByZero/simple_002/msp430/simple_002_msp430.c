/*
 * DivideByZero - simple_002
 * Architecture: MSP430 (GCC)
 */

#include <stdint.h>

#define __interrupt

void __enable_interrupt(void) {}
void __disable_interrupt(void) {}

int rand(void);

volatile int simple_002_x, simple_002_y, simple_002_z;

void simple_002_msp430_main(void) {
    simple_002_x = rand();
    simple_002_y = rand();
    if (simple_002_x < simple_002_y) {
        simple_002_z = 1 / (simple_002_x - simple_002_y);
    }
}

#pragma vector = TIMER0_A0_VECTOR
__interrupt void simple_002_msp430_isr_1(void) {
    simple_002_x++;
    simple_002_y--;
}

#pragma vector = USCI_A0_VECTOR
__interrupt void simple_002_msp430_isr_2(void) {
    simple_002_x++;
    simple_002_y--;
    if (simple_002_x == simple_002_y) {
        simple_002_x++;
        simple_002_y--;
    }
}
