/*
 * multiwordDatarace - simple_004
 * Architecture: ARM (Cortex-M / CMSIS)
 */

#include <stdint.h>

typedef enum {
  TIM2_IRQn = 28
} IRQn_Type;

void __enable_irq(void) {}
void __disable_irq(void) {}
void NVIC_EnableIRQ(IRQn_Type irqn) { (void)irqn; }
void NVIC_DisableIRQ(IRQn_Type irqn) { (void)irqn; }
void NVIC_SetPriority(IRQn_Type irqn, int priority) {
  (void)irqn;
  (void)priority;
}

void init(void);
void idlerun(void);

volatile uint64_t sequ = 0;
volatile unsigned char packet[4];

void simple_004_arm_main(void) {
    init();
    packet[0] = (unsigned char)(sequ & 0xffU);
    idlerun();
}

void TIM2_IRQHandler(void) {
    sequ = sequ + 1;
}

void USART1_IRQHandler(void) {
    sequ = sequ + 1;
}
