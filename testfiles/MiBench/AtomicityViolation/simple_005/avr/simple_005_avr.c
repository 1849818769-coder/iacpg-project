/*
 * AtomicityViolation - simple_005 (hard)
 * Architecture: AVR
 *
 * AVR has no selective IRQ disable. Two ISRs can preempt main.
 * Main uses cli() to protect, but the R1 read happens BEFORE cli().
 * The disable does not cover the full R-M-W sequence.
 */

#include "../../common.h"

#define ISR(vector) void vector(void)

void sei(void) {}
void cli(void) {}

volatile int shared_counter;

void simple_005_avr_main(void) {
    init();
    sei();

    int tmp = shared_counter;   /* R1 — exposed, no cli yet */

    cli();                      /* disable AFTER R1 */
    tmp = tmp + 1;
    shared_counter = tmp;       /* W1 — protected by cli */
    sei();
}

ISR(TIMER1_OVF_vect) {
    shared_counter = 0;
}

ISR(USART_RX_vect) {
    shared_counter = shared_counter + 10;
}
