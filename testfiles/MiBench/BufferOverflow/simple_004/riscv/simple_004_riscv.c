/*
 * BufferOverflow - simple_004
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
typedef unsigned int uint;
int simple_004_global_array[BUFFER_SIZE];

void simple_004_riscv_main(void) {
  for (uint i = 0; i < BUFFER_SIZE; i++) {
    if (simple_004_global_array[i] == 0) {
      return;
    }
  }
}

void MachineTimer_IRQHandler(void) {
  for (uint i = 0; i < BUFFER_SIZE; i++) {
    simple_004_global_array[i] = 0;
  }
}
