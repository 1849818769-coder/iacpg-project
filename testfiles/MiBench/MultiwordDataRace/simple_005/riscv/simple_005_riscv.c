/*
 * MultiwordDataRace - simple_005 (hard)
 * Architecture: RISC-V (PLIC)
 *
 * ISR uses non-standard name 'plic_irq_dispatch'.
 */

#include <stdint.h>

typedef enum {
  MachineExternal_IRQn = 11
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

volatile int64_t timestamp;

void simple_005_riscv_main(void) {
    init();
    PLIC_SetPriority(MachineExternal_IRQn, 2);
    PLIC_EnableIRQ(MachineExternal_IRQn);
    __enable_irq();

    int64_t snap = timestamp;
    if (snap > 0) {
        idlerun();
    }
}

void plic_irq_dispatch(void) {
    timestamp = timestamp + 1;
}
