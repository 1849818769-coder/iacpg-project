/*
 * MultiwordDataRace - simple_005 (hard)
 * Architecture: AVR
 *
 * ISR uses non-standard name 'timer_tick_handler' instead of ISR(*_vect).
 */

#include "../../common.h"

void sei(void) {}
void cli(void) {}

volatile int64_t timestamp;

void simple_005_avr_main(void) {
    init();
    sei();

    int64_t snap = timestamp;
    if (snap > 0) {
        idlerun();
    }
}

/* Non-standard ISR name */
void timer_tick_handler(void) {
    timestamp = timestamp + 1;
}
