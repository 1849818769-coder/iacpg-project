/*
 * multiwordDatarace - simple_004
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

void init(void);
void idlerun(void);

volatile uint64_t sequ = 0;
volatile unsigned char packet[4];

void simple_004_riscv_main(void) {
    init();
    packet[0] = (unsigned char)(sequ & 0xffU);
    idlerun();
}

void MachineTimer_IRQHandler(void) {
    sequ = sequ + 1;
}

static void uart0_isr(void) {
    sequ = sequ + 1;
}

void MachineExternal_IRQHandler(void) {
    IRQn_Type irq = PLIC_ClaimIRQ();
    if (irq == UART0_IRQn) {
        uart0_isr();
    }
    PLIC_CompleteIRQ(irq);
}
