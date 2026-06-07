/*
 * multiwordDatarace - simple_002
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

volatile uint64_t curr_sec = 0;
volatile uint32_t sec_high = 1;
volatile uint32_t sec_low = 2;
volatile uint64_t front_sec = 0;

void simple_002_riscv_main(void) {
    init();
    idlerun();
    front_sec = curr_sec;
}

void MachineTimer_IRQHandler(void) {
    curr_sec = ((uint64_t)sec_high << 32) | sec_low;
}
