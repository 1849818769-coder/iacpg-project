/*
 * multiwordDatarace - simple_001
 * Architecture: AVR (avr-libc)
 */

#include <stdint.h>

#define ISR(vector) void vector(void)

void sei(void) {}
void cli(void) {}

void init(void);
void idlerun(void);

volatile int64_t down_counter_ms = 0;

void simple_001_avr_main(void) {
    cli();
    init();
    sei();
    down_counter_ms = 500;
    idlerun();
}

ISR(TIM2_vect) {
    down_counter_ms = down_counter_ms - 1;
}
