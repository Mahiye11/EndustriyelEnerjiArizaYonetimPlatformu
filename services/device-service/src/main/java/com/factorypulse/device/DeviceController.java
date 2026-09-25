package com.factorypulse.device;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;
@RestController @RequestMapping("/api/v1/devices") class DeviceController {
  record Device(@NotBlank String id, @NotBlank String factoryId, @NotBlank String lineName, @NotBlank String name, @Positive double powerThreshold, @Positive double temperatureThreshold) {}
  record Thresholds(@Positive double powerKw, @Positive double temperatureC) {}
  private final Map<String, Device> devices = new ConcurrentHashMap<>();
  DeviceController() { devices.put("machine-42", new Device("machine-42", "factory-istanbul", "Hat A", "CNC Freze 42", 20, 75)); }
  @GetMapping Collection<Device> list(@RequestHeader("X-Factory-Id") String factoryId) { return devices.values().stream().filter(d -> d.factoryId().equals(factoryId)).toList(); }
  @PostMapping @ResponseStatus(HttpStatus.CREATED) Device create(@Valid @RequestBody Device device) { if (devices.putIfAbsent(device.id(), device) != null) throw new IllegalStateException("Device already exists"); return device; }
  @PutMapping("/{id}/thresholds") Device thresholds(@PathVariable String id, @Valid @RequestBody Thresholds value) { return devices.computeIfPresent(id, (key, old) -> new Device(old.id(), old.factoryId(), old.lineName(), old.name(), value.powerKw(), value.temperatureC())); }
}

