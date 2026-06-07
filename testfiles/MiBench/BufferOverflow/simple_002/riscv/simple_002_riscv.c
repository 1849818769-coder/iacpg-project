/*
 * BufferOverflow - simple_002
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
int simple_002_global_array[BUFFER_SIZE];
uint simple_002_global_var1;
uint simple_002_global_var2;
void simple_002_Init(void);
int rand(void);

void simple_002_riscv_main(void) {
  simple_002_Init();
  if (simple_002_global_var1 < BUFFER_SIZE &&
      simple_002_global_var2 < BUFFER_SIZE) {
    simple_002_global_array[simple_002_global_var1] = 0;
    simple_002_global_array[simple_002_global_var2] = 0;
  }
}

void simple_002_Init(void) {
  simple_002_global_var1 = 0;
  simple_002_global_var2 = 0;
}

void MachineTimer_IRQHandler(void) {
  for (uint i = 0; i < BUFFER_SIZE; i++) {
    simple_002_global_var1 = 0;
    simple_002_global_var2 = rand();
  }
}
