package com.dataprocess.agent;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
@MapperScan("com.dataprocess.agent.repository")
public class DataProcessApplication {
    public static void main(String[] args) {
        SpringApplication.run(DataProcessApplication.class, args);
    }
}
