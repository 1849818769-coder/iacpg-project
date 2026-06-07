/*
 * BufferOverflow - simple_006 (hard, TN)
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

#define BUFFER_SIZE 10
int buffer[BUFFER_SIZE];
volatile unsigned int idx;

void simple_006_riscv_main(void) {
    PLIC_SetPriority(MachineTimer_IRQn, 2);
    PLIC_EnableIRQ(MachineTimer_IRQn);
    __enable_irq();

    __disable_irq();
    if (idx < BUFFER_SIZE) {
        buffer[idx] = 99;
    }
    __enable_irq();
}

void MachineTimer_IRQHandler(void) {
    idx = BUFFER_SIZE + 1;
}
