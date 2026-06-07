/*
 * MultiwordDataRace - simple_006 (hard)
 * Architecture: AVR
 */

#include "../../common.h"

#define ISR(vector) void vector(void)

void sei(void) {}
void cli(void) {}

typedef struct {
    volatile int16_t x;
    volatile int16_t y;
} coord_t;

coord_t position;

void simple_006_avr_main(void) {
    init();
    sei();

    int16_t px = position.x;
    int16_t py = position.y;
    int16_t dist = px * px + py * py;
    (void)dist;
}

ISR(TIMER1_OVF_vect) {
    position.x = position.x + 1;
    position.y = position.y + 1;
}
