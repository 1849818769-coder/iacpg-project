/*
 * BufferOverflow - simple_005 (hard)
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
volatile unsigned int index_val;

void simple_005_riscv_main(void) {
    PLIC_SetPriority(MachineTimer_IRQn, 2);
    PLIC_EnableIRQ(MachineTimer_IRQn);

    __disable_irq();
    index_val = 0;
    __enable_irq();

    if (index_val < BUFFER_SIZE) {
        buffer[index_val] = 42;
    }
}

void MachineTimer_IRQHandler(void) {
    index_val = BUFFER_SIZE + 5;
}
