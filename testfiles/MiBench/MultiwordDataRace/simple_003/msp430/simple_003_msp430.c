/*
 * multiwordDatarace - simple_003
 * Architecture: MSP430 (GCC)
 */

#include <stdint.h>

#define __interrupt

void __enable_interrupt(void) {}
void __disable_interrupt(void) {}

void init(void);
void idlerun(void);

volatile uint64_t broadcast_num = 0x1020304050607080ULL;
volatile unsigned char frame[8];

static void copy_u64_to_bytes(volatile unsigned char *dst, uint64_t value) {
    int i;
    for (i = 0; i < 8; ++i) {
        dst[i] = (unsigned char)((value >> (i * 8)) & 0xffU);
    }
}

void simple_003_msp430_main(void) {
    uint64_t snapshot_num;
    init();
    snapshot_num = broadcast_num;
    __disable_interrupt();
    copy_u64_to_bytes(frame, snapshot_num);
    __enable_interrupt();
    idlerun();
}

#pragma vector = TIMER0_A0_VECTOR
__interrupt void simple_003_msp430_isr_1(void) {
    broadcast_num = broadcast_num + 1;
}
