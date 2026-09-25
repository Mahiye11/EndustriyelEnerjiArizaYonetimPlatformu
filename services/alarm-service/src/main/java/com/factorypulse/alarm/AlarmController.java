package com.factorypulse.alarm;
import java.time.Instant;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import org.springframework.web.bind.annotation.*;
@RestController @RequestMapping("/api/v1/alarms") class AlarmController {
  record Alarm(String id, String factoryId, String deviceId, String kind, double value, double threshold, String status, String assignee, Instant createdAt) {}
  record Assignment(String technician) {}
  private final Map<String, Alarm> alarms = new ConcurrentHashMap<>();
  @GetMapping Collection<Alarm> list(@RequestHeader("X-Factory-Id") String factoryId) { return alarms.values().stream().filter(a -> a.factoryId().equals(factoryId)).toList(); }
  @PostMapping("/{id}/assign") Alarm assign(@PathVariable String id, @RequestBody Assignment input) { return alarms.computeIfPresent(id, (key, old) -> new Alarm(old.id(), old.factoryId(), old.deviceId(), old.kind(), old.value(), old.threshold(), "assigned", input.technician(), old.createdAt())); }
  @PostMapping("/{id}/resolve") Alarm resolve(@PathVariable String id) { return alarms.computeIfPresent(id, (key, old) -> new Alarm(old.id(), old.factoryId(), old.deviceId(), old.kind(), old.value(), old.threshold(), "resolved", old.assignee(), old.createdAt())); }
}

