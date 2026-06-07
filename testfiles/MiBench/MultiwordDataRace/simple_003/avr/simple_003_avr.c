/*
 * multiwordDatarace - simple_003
 * Architecture: AVR (avr-libc)
 */

#include <stdint.h>

#define ISR(vector) void vector(void)

void sei(void) {}
void cli(void) {}

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

void simple_003_avr_main(void) {
    uint64_t snapshot_num;
    init();
    snapshot_num = broadcast_num;
    cli();
    copy_u64_to_bytes(frame, snapshot_num);
    sei();
    idlerun();
}

ISR(TIM2_vect) {
    broadcast_num = broadcast_num + 1;
}
