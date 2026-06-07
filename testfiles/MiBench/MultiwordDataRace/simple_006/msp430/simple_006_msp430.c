/*
 * MultiwordDataRace - simple_006 (hard)
 * Architecture: MSP430
 */

#include "../../common.h"

#define __interrupt

void __enable_interrupt(void) {}
void __disable_interrupt(void) {}

typedef struct {
    volatile int16_t x;
    volatile int16_t y;
} coord_t;

coord_t position;

void simple_006_msp430_main(void) {
    init();
    __enable_interrupt();

    int16_t px = position.x;
    int16_t py = position.y;
    int16_t dist = px * px + py * py;
    (void)dist;
}

__interrupt void TIMER0_A0_ISR(void) {
    position.x = position.x + 1;
    position.y = position.y + 1;
}
