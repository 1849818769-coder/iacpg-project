/*
 * AtomicityViolation - simple_005 (hard)
 * Architecture: MSP430
 *
 * MSP430 has no selective IRQ disable. Two ISRs can preempt main.
 * Main uses __disable_interrupt() but R1 happens before the disable.
 */

#include "../../common.h"

#define __interrupt

void __enable_interrupt(void) {}
void __disable_interrupt(void) {}

volatile int shared_counter;

void simple_005_msp430_main(void) {
    init();
    __enable_interrupt();

    int tmp = shared_counter;       /* R1 — exposed */

    __disable_interrupt();          /* disable AFTER R1 */
    tmp = tmp + 1;
    shared_counter = tmp;           /* W1 — protected */
    __enable_interrupt();
}

__interrupt void TIMER0_A0_ISR(void) {
    shared_counter = 0;
}

__interrupt void USCI_A0_ISR(void) {
    shared_counter = shared_counter + 10;
}
