/*
 * BufferOverflow - simple_006 (hard, TN)
 * Architecture: AVR
 */

#include "../../common.h"

#define ISR(vector) void vector(void)

void sei(void) {}
void cli(void) {}

#define BUFFER_SIZE 10
int buffer[BUFFER_SIZE];
volatile unsigned int idx;

void simple_006_avr_main(void) {
    init();
    sei();

    cli();
    if (idx < BUFFER_SIZE) {
        buffer[idx] = 99;
    }
    sei();
}

ISR(TIMER1_OVF_vect) {
    idx = BUFFER_SIZE + 1;
}
