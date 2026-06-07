/*
 * MultiwordDataRace - simple_006 (hard)
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

typedef struct {
    volatile int32_t x;
    volatile int32_t y;
} coord_t;

coord_t position;

void simple_006_riscv_main(void) {
    init();
    PLIC_SetPriority(MachineTimer_IRQn, 2);
    PLIC_EnableIRQ(MachineTimer_IRQn);
    __enable_irq();

    int32_t px = position.x;
    int32_t py = position.y;
    int32_t dist = px * px + py * py;
    (void)dist;
}

void MachineTimer_IRQHandler(void) {
    position.x = position.x + 1;
    position.y = position.y + 1;
}
