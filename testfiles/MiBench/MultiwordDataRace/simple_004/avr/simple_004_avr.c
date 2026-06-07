/*
 * multiwordDatarace - simple_004
 * Architecture: AVR (avr-libc)
 */

#include <stdint.h>

#define ISR(vector) void vector(void)

void sei(void) {}
void cli(void) {}

void init(void);
void idlerun(void);

volatile uint64_t sequ = 0;
volatile unsigned char packet[4];

void simple_004_avr_main(void) {
    init();
    packet[0] = (unsigned char)(sequ & 0xffU);
    idlerun();
}

ISR(TIM2_vect) {
    sequ = sequ + 1;
}

ISR(USART1_vect) {
    sequ = sequ + 1;
}
