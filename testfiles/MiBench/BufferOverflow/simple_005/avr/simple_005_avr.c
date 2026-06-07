/*
 * BufferOverflow - simple_005 (hard)
 * Architecture: AVR
 */

#include "../../common.h"

#define ISR(vector) void vector(void)

void sei(void) {}
void cli(void) {}

#define BUFFER_SIZE 10
int buffer[BUFFER_SIZE];
volatile unsigned int index_val;

void simple_005_avr_main(void) {
    init();

    cli();
    index_val = 0;
    sei();

    if (index_val < BUFFER_SIZE) {
        buffer[index_val] = 42;
    }
}

ISR(TIMER1_OVF_vect) {
    index_val = BUFFER_SIZE + 5;
}
