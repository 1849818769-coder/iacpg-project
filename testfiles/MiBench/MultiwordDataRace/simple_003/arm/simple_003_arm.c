/*
 * multiwordDatarace - simple_003
 * Architecture: ARM (Cortex-M / CMSIS)
 */

#include <stdint.h>

typedef enum {
  TIM2_IRQn = 28
} IRQn_Type;

void __enable_irq(void) {}
void __disable_irq(void) {}
void NVIC_EnableIRQ(IRQn_Type irqn) { (void)irqn; }
void NVIC_DisableIRQ(IRQn_Type irqn) { (void)irqn; }
void NVIC_SetPriority(IRQn_Type irqn, int priority) {
  (void)irqn;
  (void)priority;
}

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

void simple_003_arm_main(void) {
    uint64_t snapshot_num;
    init();
    snapshot_num = broadcast_num;
    __disable_irq();
    copy_u64_to_bytes(frame, snapshot_num);
    __enable_irq();
    idlerun();
}

void TIM2_IRQHandler(void) {
    broadcast_num = broadcast_num + 1;
}
