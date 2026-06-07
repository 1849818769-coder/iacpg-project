/*
 * multiwordDatarace - simple_002
 * Architecture: AVR (avr-libc)
 */

#include <stdint.h>

#define ISR(vector) void vector(void)

void sei(void) {}
void cli(void) {}

void init(void);
void idlerun(void);

volatile uint64_t curr_sec = 0;
volatile uint32_t sec_high = 1;
volatile uint32_t sec_low = 2;
volatile uint64_t front_sec = 0;

void simple_002_avr_main(void) {
    init();
    idlerun();
    front_sec = curr_sec;
}

ISR(TIM2_vect) {
    curr_sec = ((uint64_t)sec_high << 32) | sec_low;
}
