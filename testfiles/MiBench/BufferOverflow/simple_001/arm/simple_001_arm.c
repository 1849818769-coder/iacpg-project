/*
 * BufferOverflow - simple_001
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

#define BUFFER_SIZE 10
int simple_001_global_array[BUFFER_SIZE];
unsigned int simple_001_global_var;
void simple_001_Init(void);

void simple_001_arm_main(void) {
  simple_001_Init();
  if(simple_001_global_var < BUFFER_SIZE){
    simple_001_global_array[simple_001_global_var] = 0;
  }
}

void simple_001_Init(void) {
  simple_001_global_var = 1;
}

void TIM2_IRQHandler(void) {
  simple_001_global_var = 0;
  simple_001_global_var = BUFFER_SIZE + 1;
}
