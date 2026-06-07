/*
 * AtomicityViolation - simple_006 (hard)
 * Architecture: MSP430
 */

#include "../../common.h"

#define __interrupt

void __enable_interrupt(void) {}
void __disable_interrupt(void) {}

volatile int state;

static int get_state(void) { return state; }
static void set_state(int v) { state = v; }

void simple_006_msp430_main(void) {
    init();
    __enable_interrupt();

    int old = get_state();
    int new_val = old + 1;
    set_state(new_val);
}

__interrupt void TIMER0_A0_ISR(void) {
    state = 0;
}
