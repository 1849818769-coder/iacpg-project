/*
 * multiwordDatarace - simple_003
 * Architecture: RISC-V (PLIC)
 */

#include <stdint.h>

typedef enum {
  MachineTimer_IRQn = 7
} IRQn_Type;

void __enable_irq(void) {}
void __disable_irq(void) {}
void PLIC_EnableIRQ(IRQn_Type irqn) { (void)irqn; }
void PLIC_DisableIRQ(IRQn_Type irqn) { (void)irqn; }
void PLIC_SetPriority(IRQn_Type irqn, int priority) {
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

void simple_003_riscv_main(void) {
    uint64_t snapshot_num;
    init();
    snapshot_num = broadcast_num;
    __disable_irq();
    copy_u64_to_bytes(frame, snapshot_num);
    __enable_irq();
    idlerun();
}

void MachineTimer_IRQHandler(void) {
    broadcast_num = broadcast_num + 1;
}
