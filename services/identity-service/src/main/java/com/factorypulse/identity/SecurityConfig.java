package com.factorypulse.identity;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.Customizer;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.web.SecurityFilterChain;
@Configuration class SecurityConfig { @Bean SecurityFilterChain apiSecurity(HttpSecurity http) throws Exception { return http.csrf(csrf -> csrf.disable()).authorizeHttpRequests(auth -> auth.requestMatchers("/actuator/health", "/api/v1/auth/login").permitAll().anyRequest().authenticated()).httpBasic(Customizer.withDefaults()).build(); } }

