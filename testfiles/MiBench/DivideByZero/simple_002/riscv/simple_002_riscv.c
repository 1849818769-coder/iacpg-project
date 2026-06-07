/*
 * DivideByZero - simple_002
 * Architecture: RISC-V (PLIC)
 */

#include <stdint.h>

typedef enum {
  MachineTimer_IRQn = 7,
  UART0_IRQn = 10
} IRQn_Type;

void __enable_irq(void) {}
void __disable_irq(void) {}
void PLIC_EnableIRQ(IRQn_Type irqn) { (void)irqn; }
void PLIC_DisableIRQ(IRQn_Type irqn) { (void)irqn; }
void PLIC_SetPriority(IRQn_Type irqn, int priority) {
  (void)irqn;
  (void)priority;
}
IRQn_Type PLIC_ClaimIRQ(void) { return MachineTimer_IRQn; }
void PLIC_CompleteIRQ(IRQn_Type irqn) { (void)irqn; }

int rand(void);

volatile int simple_002_x, simple_002_y, simple_002_z;

void simple_002_riscv_main(void) {
    simple_002_x = rand();
    simple_002_y = rand();
    if (simple_002_x < simple_002_y) {
        simple_002_z = 1 / (simple_002_x - simple_002_y);
    }
}

void MachineTimer_IRQHandler(void) {
    simple_002_x++;
    simple_002_y--;
}

static void uart0_isr(void) {
    simple_002_x++;
    simple_002_y--;
    if (simple_002_x == simple_002_y) {
        simple_002_x++;
        simple_002_y--;
    }
}

void MachineExternal_IRQHandler(void) {
    IRQn_Type irq = PLIC_ClaimIRQ();
    if (irq == UART0_IRQn) {
        uart0_isr();
    }
    PLIC_CompleteIRQ(irq);
}
