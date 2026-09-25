package com.factorypulse.identity;
import java.util.Map;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
@RestController @RequestMapping("/api/v1/auth") class IdentityController {
  record Login(String email, String password) {}
  @PostMapping("/login") ResponseEntity<?> login(@RequestBody Login login) {
    if (!"factorypulse".equals(login.password())) return ResponseEntity.status(401).body(Map.of("code", "INVALID_CREDENTIALS", "message", "Email or password is incorrect"));
    String role = login.email().startsWith("admin") ? "ADMIN" : login.email().startsWith("tech") ? "TECHNICIAN" : "OPERATOR";
    return ResponseEntity.ok(Map.of("subject", login.email(), "role", role, "factoryId", "factory-istanbul", "tokenType", "migration-placeholder"));
  }
}

