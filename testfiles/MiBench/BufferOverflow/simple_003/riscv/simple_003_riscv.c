/*
 * BufferOverflow - simple_003
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
typedef unsigned char uchar;
int simple_003_global_array[BUFFER_SIZE];
uchar simple_003_global_flag = 0;
uint simple_003_global_var1;
uint simple_003_global_var2;
void simple_003_Init(void);
void simple_003_Adjust(void);
int rand(void);

void simple_003_riscv_main(void) {
  simple_003_Init();
  PLIC_SetPriority(MachineTimer_IRQn, 2);
  PLIC_EnableIRQ(MachineTimer_IRQn);
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

void MachineTimer_IRQHandler(void) {
  simple_003_global_flag = 1;
  simple_003_global_var1 = BUFFER_SIZE + 5;
}
