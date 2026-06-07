/*
 * AtomicityViolation - simple_006 (hard)
 * Architecture: AVR
 */

#include "../../common.h"

#define ISR(vector) void vector(void)

void sei(void) {}
void cli(void) {}

volatile int state;

static int get_state(void) { return state; }
static void set_state(int v) { state = v; }

void simple_006_avr_main(void) {
    init();
    sei();

    int old = get_state();
    int new_val = old + 1;
    set_state(new_val);
}

ISR(TIMER1_OVF_vect) {
    state = 0;
}
