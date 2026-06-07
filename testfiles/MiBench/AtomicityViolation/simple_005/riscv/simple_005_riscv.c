/*
 * AtomicityViolation - simple_005 (hard)
 * Architecture: RISC-V (PLIC)
 *
 * Selective masking: PLIC_DisableIRQ disables MachineTimer (low-priority),
 * but MachineExternal (high-priority) remains enabled.
 */

#include <stdint.h>

typedef enum {
  MachineTimer_IRQn = 7,
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
int rand(void);

volatile int shared_counter;

void simple_005_riscv_main(void) {
    init();
    PLIC_SetPriority(MachineTimer_IRQn, 3);
    PLIC_SetPriority(MachineExternal_IRQn, 1);
    PLIC_EnableIRQ(MachineTimer_IRQn);
    PLIC_EnableIRQ(MachineExternal_IRQn);
    __enable_irq();

    PLIC_DisableIRQ(MachineTimer_IRQn);

    int tmp = shared_counter;
    tmp = tmp + 1;
    shared_counter = tmp;

    PLIC_EnableIRQ(MachineTimer_IRQn);
}

void MachineTimer_IRQHandler(void) {
    shared_counter = 0;
}

void MachineExternal_IRQHandler(void) {
    shared_counter = shared_counter + 10;
}
