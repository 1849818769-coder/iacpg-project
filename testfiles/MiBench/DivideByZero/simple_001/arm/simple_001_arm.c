/*
 * DivideByZero - simple_001
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

int rand(void);
void print(int);

volatile int simple_001_d;

void simple_001_arm_main(void) {
    simple_001_d = rand();
    if (simple_001_d != 0) {
        print(10 / simple_001_d);
    }
}

void TIM2_IRQHandler(void) {
    simple_001_d--;
}

void USART1_IRQHandler(void) {
    simple_001_d--;
    if (simple_001_d <= 0) {
        simple_001_d = 1;
    }
}
