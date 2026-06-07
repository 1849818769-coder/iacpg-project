/*
 * BufferOverflow - simple_003
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
typedef unsigned int uint;
typedef unsigned char uchar;
int simple_003_global_array[BUFFER_SIZE];
uchar simple_003_global_flag = 0;
uint simple_003_global_var1;
uint simple_003_global_var2;
void simple_003_Init(void);
void simple_003_Adjust(void);
int rand(void);

void simple_003_arm_main(void) {
  simple_003_Init();
  NVIC_SetPriority(TIM2_IRQn, 2);
  NVIC_EnableIRQ(TIM2_IRQn);
  __enable_irq();
  simple_003_Adjust();
  simple_003_global_array[simple_003_global_var1] = 0;
  simple_003_global_array[simple_003_global_var2] = 0;
}

void simple_003_Init(void) {
  simple_003_global_flag = 0;
  simple_003_global_var1 = 0;
  simple_003_global_var2 = 0;
}

void simple_003_Adjust(void) {
  if(simple_003_global_flag){
    simple_003_global_var1 = rand() % BUFFER_SIZE;
    simple_003_global_flag = 0;
  }else{
    simple_003_global_var1 = rand() % BUFFER_SIZE;
  }
}

void TIM2_IRQHandler(void) {
  simple_003_global_flag = 1;
  simple_003_global_var1 = BUFFER_SIZE + 5;
}
