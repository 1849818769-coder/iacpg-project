/*
 * MultiwordDataRace - simple_005 (hard)
 * Architecture: MSP430
 *
 * ISR uses non-standard name 'on_timer_event' instead of __interrupt *_ISR.
 */

#include "../../common.h"

void __enable_interrupt(void) {}
void __disable_interrupt(void) {}

volatile int64_t timestamp;

void simple_005_msp430_main(void) {
    init();
    __enable_interrupt();

    int64_t snap = timestamp;
    if (snap > 0) {
        idlerun();
    }
}

/* Non-standard ISR name */
void on_timer_event(void) {
    timestamp = timestamp + 1;
}
